//=====================================================================
// Project : 4 core MESI cache design
// File Name : main_func_lv1_dl.sv
// Description : main function block for level 1 data level
// Designer : Yuhao Yang
//=====================================================================
// Notable Change History:
// Date By   Version Change Description
// 2016/4/16  1.0     Initial Release
//=====================================================================
`include "def_lv1.sv"
//keep lv2_rd seperated from bus_rd. level 2 responds to both
module main_func_lv1_dl #(
                           parameter ASSOC              = `ASSOC_LV1              ,
                           parameter ASSOC_WID          = `ASSOC_WID_LV1          ,
                           parameter DATA_WID           = `DATA_WID_LV1           ,
                           parameter ADDR_WID           = `ADDR_WID_LV1           ,
                           parameter INDEX_MSB          = `INDEX_MSB_LV1          ,
                           parameter INDEX_LSB          = `INDEX_LSB_LV1          ,
                           parameter TAG_MSB            = `TAG_MSB_LV1            ,
                           parameter TAG_LSB            = `TAG_LSB_LV1            ,
                           parameter CACHE_DATA_WID     = `CACHE_DATA_WID_LV1     ,
                           parameter CACHE_TAG_MSB      = `CACHE_TAG_MSB_LV1      ,
                           parameter CACHE_TAG_LSB      = `CACHE_TAG_LSB_LV1      ,
                           parameter CACHE_DEPTH        = `CACHE_DEPTH_LV1        ,
                           parameter CACHE_MESI_MSB     = `CACHE_MESI_MSB_LV1     ,
                           parameter CACHE_MESI_LSB     = `CACHE_MESI_LSB_LV1     ,
                           parameter CACHE_TAG_MESI_WID = `CACHE_TAG_MESI_WID_LV1 ,
                           parameter MESI_WID           = `MESI_WID_LV1           ,
                           parameter OFFSET_WID         = `OFFSET_WID_LV1         ,
                           parameter TAG_WID            = `TAG_WID_LV1
                       )(
                         input                               clk                     ,
                         input      [1                  : 0] core_id                 ,
                         inout      [DATA_WID - 1       : 0] data_bus_lv1_lv2        ,
                         inout      [ADDR_WID - 1       : 0] addr_bus_lv1_lv2        ,
                         inout      [DATA_WID - 1       : 0] data_bus_cpu_lv1        ,
                         input      [ADDR_WID - 1       : 0] addr_bus_cpu_lv1        ,
                         output reg                          lv2_rd                  ,
                         output reg                          lv2_wr                  ,
                         input                               lv2_wr_done             ,
                         input                               cpu_rd                  ,
                         input                               cpu_wr                  ,
                         output reg                          cpu_wr_done             ,
                         inout                               bus_rd                  ,
                         inout                               bus_rdx                 ,
                         input                               bus_lv1_lv2_gnt_proc    ,
                         output reg                          bus_lv1_lv2_req_proc_dl ,
                         input                               bus_lv1_lv2_gnt_snoop   ,
                         output reg                          bus_lv1_lv2_req_snoop   ,
                         input      [INDEX_MSB  : INDEX_LSB] index_proc              ,
                         input      [INDEX_MSB  : INDEX_LSB] index_snoop             ,
                         input      [TAG_MSB    :   TAG_LSB] tag_proc                ,
                         input      [TAG_MSB    :   TAG_LSB] tag_snoop               ,
                         input                               blk_hit_proc            ,
                         input                               blk_hit_snoop           ,
                         input                               blk_free                ,
                         input      [ASSOC_WID - 1      : 0] blk_access_proc         ,
                         input      [ASSOC_WID - 1      : 0] blk_access_snoop        ,
                         input      [ASSOC_WID - 1      : 0] lru_replacement_proc    ,
                         output reg                          data_in_bus_cpu_lv1_dl  ,
                         inout                               data_in_bus_lv1_lv2     ,
                         inout                               invalidate              ,
                         input                               all_invalidation_done   ,
                         input      [MESI_WID - 1       : 0] updated_mesi_proc       ,
                         input      [MESI_WID - 1       : 0] updated_mesi_snoop      ,
                         output     [MESI_WID - 1       : 0] current_mesi_proc       ,
                         output     [MESI_WID - 1       : 0] current_mesi_snoop      ,
                         output reg                          shared_local            ,
                         output reg                          cp_in_cache             ,
                         output reg                          invalidation_done       ,
                         output reg [ASSOC_WID - 1      : 0] blk_accessed_main       ,
                         output reg                          lru_update              ,
                         output reg [ASSOC*MESI_WID - 1 : 0] cache_proc_mesi         ,
                         output reg [ASSOC*MESI_WID - 1 : 0] cache_snoop_mesi        ,
                         output reg [ASSOC*TAG_WID - 1  : 0] cache_proc_tag          ,
                         output reg [ASSOC*TAG_WID - 1  : 0] cache_snoop_tag
                         );

    parameter INVALID   = 2'b00;
    parameter SHARED    = 2'b01;
    parameter EXCLUSIVE = 2'b10;
    parameter MODIFIED  = 2'b11;

    reg [CACHE_DATA_WID - 1     : 0] cache_var        [0 : CACHE_DEPTH - 1];
    reg [CACHE_TAG_MESI_WID - 1 : 0] cache_proc_contr [0 : CACHE_DEPTH - 1];

    reg [DATA_WID - 1 : 0] data_bus_lv1_lv2_reg;
    reg [ADDR_WID - 1 : 0] addr_bus_lv1_lv2_reg;
    reg [DATA_WID - 1 : 0] data_bus_cpu_lv1_reg;
    reg                    data_in_bus_lv1_lv2_reg;
    reg                    bus_rd_reg;
    reg                    bus_rdx_reg;
    reg                    invalidate_reg;

    initial begin
        for (int i = 0; i<CACHE_DEPTH; i++) begin
            cache_var[i]        = {CACHE_DATA_WID{1'b0}};
            cache_proc_contr[i] = {CACHE_TAG_MESI_WID{1'b0}};
        end
    end

    assign data_bus_lv1_lv2    = data_bus_lv1_lv2_reg;
    assign addr_bus_lv1_lv2    = addr_bus_lv1_lv2_reg;
    assign data_bus_cpu_lv1    = data_bus_cpu_lv1_reg;
    assign data_in_bus_lv1_lv2 = data_in_bus_lv1_lv2_reg;
    assign bus_rd              = bus_rd_reg;
    assign bus_rdx             = bus_rdx_reg;
    assign invalidate          = invalidate_reg;

    always @(posedge clk) begin
        if(lru_update) //restrict lru_update to one clock cycle
            lru_update <= 1'b0;
        else
            lru_update <= blk_hit_proc;
    end

    generate
        for(genvar gi = 1; gi<=ASSOC; gi++) begin
            assign cache_proc_mesi [gi*MESI_WID - 1 : (gi-1)*MESI_WID] = cache_proc_contr[{index_proc,{ASSOC_WID{1'b0}}}+gi-1][CACHE_MESI_MSB : CACHE_MESI_LSB];
            assign cache_proc_tag  [gi*TAG_WID - 1  : (gi-1)*TAG_WID ] = cache_proc_contr[{index_proc,{ASSOC_WID{1'b0}}}+gi-1][CACHE_TAG_MSB  : CACHE_TAG_LSB ];
            assign cache_snoop_mesi[gi*MESI_WID - 1 : (gi-1)*MESI_WID] = cache_proc_contr[{index_snoop,{ASSOC_WID{1'b0}}}+gi-1][CACHE_MESI_MSB : CACHE_MESI_LSB];
            assign cache_snoop_tag [gi*TAG_WID - 1  : (gi-1)*TAG_WID ] = cache_proc_contr[{index_snoop,{ASSOC_WID{1'b0}}}+gi-1][CACHE_TAG_MSB  : CACHE_TAG_LSB ];
        end
    endgenerate

    assign current_mesi_proc  = (cpu_rd|cpu_wr)? `CACHE_CURRENT_MESI_PROC : 2'b00;
    assign current_mesi_snoop = `CACHE_CURRENT_MESI_SNOOP;

    always @(posedge clk) begin
        data_bus_cpu_lv1_reg    <= 32'hz;
        data_bus_lv1_lv2_reg    <= 32'hz;
        addr_bus_lv1_lv2_reg    <= 32'hz;
        data_in_bus_lv1_lv2_reg <= 1'bz;
        invalidate_reg          <= 1'bz;
        bus_rd_reg              <= 1'bz;
        bus_rdx_reg             <= 1'bz;
        invalidation_done       <= 1'b0;
        bus_lv1_lv2_req_proc_dl <= 1'b1; // BUG: should be 1'b0
        bus_lv1_lv2_req_snoop   <= 1'b0;
        data_in_bus_cpu_lv1_dl  <= 1'b0;
        lv2_rd                  <= 1'b0;
        lv2_wr                  <= 1'b0;
        shared_local            <= 1'b0;
        cpu_wr_done             <= 1'b0;
        cp_in_cache             <= 1'b0;

        // proc side
        if(cpu_rd && blk_hit_proc) begin
            data_bus_cpu_lv1_reg   <= cache_var[{index_proc,blk_access_proc}];
            data_in_bus_cpu_lv1_dl <= 1'b1;
            blk_accessed_main      <= blk_access_proc;
        end
        // read miss
        else if(cpu_rd && !blk_hit_proc) begin
            bus_lv1_lv2_req_proc_dl <= 1'b1;
            if(bus_lv1_lv2_gnt_proc) begin
                bus_rd_reg           <= 1'b0;
                invalidate_reg       <= 1'b0;
                bus_rdx_reg          <= 1'b0;
            end
            // free block
            if(blk_free && bus_lv1_lv2_gnt_proc) begin
                bus_rd_reg           <= 1'b1;
                invalidate_reg       <= 1'b0;
                bus_rdx_reg          <= 1'b0;
                lv2_rd               <= 1'b1;
                addr_bus_lv1_lv2_reg <= {tag_proc, index_proc, 2'b00};
                if(data_in_bus_lv1_lv2) begin
                    cache_var[{index_proc,blk_access_proc}] <= data_bus_lv1_lv2;
                    `CACHE_CURRENT_MESI_PROC                <= updated_mesi_proc;
                    `CACHE_CURRENT_TAG_PROC                 <= tag_proc;
                    bus_lv1_lv2_req_proc_dl <= 1'b0;
                    lv2_rd                  <= 1'b0;
                    addr_bus_lv1_lv2_reg    <= 32'hz;
                    bus_rd_reg              <= 1'b0;
                    invalidate_reg          <= 1'b0;
                    bus_rdx_reg             <= 1'b0;
                end
            end
            // replacement
            else if(!blk_free) begin
                case (`CACHE_CURRENT_MESI_PROC)
                    SHARED:
                        `CACHE_CURRENT_MESI_PROC <= INVALID;
                    EXCLUSIVE:
                        `CACHE_CURRENT_MESI_PROC <= INVALID;
                    MODIFIED: begin
                        if(bus_lv1_lv2_gnt_proc) begin
                            addr_bus_lv1_lv2_reg <= {`CACHE_CURRENT_TAG_PROC,index_proc,2'b00};
                            lv2_wr               <= 1'b1;
                            data_bus_lv1_lv2_reg <= cache_var[{index_proc,blk_access_proc}];
                            if(lv2_wr_done) begin
                                `CACHE_CURRENT_MESI_PROC <= INVALID;
                                 addr_bus_lv1_lv2_reg    <= 32'hz;
                                 lv2_wr                  <= 1'b0;
                                 data_bus_lv1_lv2_reg    <= 32'hz;
                            end
                        end
                    end
                    default:
                        `CACHE_CURRENT_MESI_PROC <= INVALID;
                endcase

            end
        end

        //proc write
        if(cpu_wr) begin
            bus_lv1_lv2_req_proc_dl <= 1'b1;
            if(bus_lv1_lv2_gnt_proc) begin
                bus_rd_reg           <= 1'b0;
                invalidate_reg       <= 1'b0;
                bus_rdx_reg          <= 1'b0;
            end
            // write hit
            if(blk_hit_proc) begin
                case (`CACHE_CURRENT_MESI_PROC)
                    SHARED: begin
                        if(bus_lv1_lv2_gnt_proc) begin
                            invalidate_reg       <= 1'b1;
                            bus_rd_reg           <= 1'b0;
                            bus_rdx_reg          <= 1'b0;
                            addr_bus_lv1_lv2_reg <= {tag_proc,index_proc,2'b00};
                            if(all_invalidation_done) begin
                                cache_var[{index_proc,blk_access_proc}] <= data_bus_cpu_lv1;
                                `CACHE_CURRENT_MESI_PROC                <= updated_mesi_proc;
                                cpu_wr_done                             <= 1'b1;
                                blk_accessed_main                       <= blk_access_proc;
                                bus_lv1_lv2_req_proc_dl                 <= 1'b0;
                                invalidate_reg                          <= 1'b0;
                                addr_bus_lv1_lv2_reg                    <= 32'hz;
                            end
                        end
                    end
                    default: begin
                        cache_var[{index_proc,blk_access_proc}] <= data_bus_cpu_lv1;
                        `CACHE_CURRENT_MESI_PROC                <= updated_mesi_proc;
                        cpu_wr_done                             <= 1'b1;
                        blk_accessed_main                       <= blk_access_proc;
                        bus_lv1_lv2_req_proc_dl                 <= 1'b0;
                    end
                endcase
            end
            // write miss
            else if (blk_free) begin
                if(bus_lv1_lv2_gnt_proc) begin
                    bus_rdx_reg     <= 1'b1;
                    bus_rd_reg      <= 1'b0;
                    invalidate_reg  <= 1'b0;
                    lv2_rd          <= 1'b1;
                    addr_bus_lv1_lv2_reg <= {tag_proc,index_proc,2'b00};
                    if(data_in_bus_lv1_lv2) begin
                        cache_var[{index_proc,blk_access_proc}] <= data_bus_lv1_lv2;
                        `CACHE_CURRENT_MESI_PROC                <= updated_mesi_proc;
                        `CACHE_CURRENT_TAG_PROC                 <= tag_proc;
                        bus_lv1_lv2_req_proc_dl                 <= 1'b0;
                        lv2_rd                                  <= 1'b0;
                        bus_rdx_reg                             <= 1'b0;
                        bus_rd_reg                              <= 1'b0;
                        invalidate_reg                          <= 1'b0;
                        addr_bus_lv1_lv2_reg                    <= 32'hz;
                    end
                end
            end
            // replacement
            else begin
                case (`CACHE_CURRENT_MESI_PROC)
                    SHARED:
                        `CACHE_CURRENT_MESI_PROC <= INVALID;
                    EXCLUSIVE:
                        `CACHE_CURRENT_MESI_PROC <= INVALID;
                    MODIFIED: begin
                        if(bus_lv1_lv2_gnt_proc) begin
                            bus_rdx_reg              <= 1'b0;
                            bus_rd_reg               <= 1'b0;
                            invalidate_reg           <= 1'b0;
                            addr_bus_lv1_lv2_reg <= {`CACHE_CURRENT_TAG_PROC,index_proc,2'b00};
                            data_bus_lv1_lv2_reg <= cache_var[{index_proc,blk_access_proc}];
                            lv2_wr                  <= 1'b1;
                            if (lv2_wr_done) begin
                                `CACHE_CURRENT_MESI_PROC <= INVALID;
                                lv2_wr                   <= 1'b0;
                            end
                        end
                    end
                    default:
                        `CACHE_CURRENT_MESI_PROC <= INVALID;
                endcase
            end
        end

        // snoop side
        if(blk_hit_snoop && (bus_lv1_lv2_gnt_proc != 1'b1)) begin
            if(invalidate && !invalidation_done) begin
                shared_local              <= 1'b1;
                `CACHE_CURRENT_MESI_SNOOP <= updated_mesi_snoop;
                invalidation_done         <= 1'b1;
            end
            else if(bus_rdx) begin
                cp_in_cache           <= 1'b1;
                case (`CACHE_CURRENT_MESI_SNOOP)
                    SHARED: begin
                        shared_local              <= 1'b1;
                        `CACHE_CURRENT_MESI_SNOOP <= updated_mesi_snoop;
                    end
                    MODIFIED: begin
                        bus_lv1_lv2_req_snoop <= 1'b1;
                        if(bus_lv1_lv2_gnt_snoop) begin
                            data_bus_lv1_lv2_reg <= cache_var[{index_snoop,blk_access_snoop}];
                            lv2_wr <= 1'b1;
                            if(lv2_wr_done) begin
                                `CACHE_CURRENT_MESI_SNOOP <= updated_mesi_snoop;
                                lv2_wr                    <= 1'b0;
                                data_bus_lv1_lv2_reg      <= 32'hz;
                            end
                        end
                    end
                    default: `CACHE_CURRENT_MESI_SNOOP <= updated_mesi_snoop;
                endcase
            end
            else if(bus_rd) begin
                bus_lv1_lv2_req_snoop <= 1'b1;
                cp_in_cache           <= 1'b1;
                if(data_in_bus_lv1_lv2 && !bus_lv1_lv2_gnt_snoop)
                    bus_lv1_lv2_req_snoop <= 1'b0;
                if(bus_lv1_lv2_gnt_snoop) begin
                    case (`CACHE_CURRENT_MESI_SNOOP)
                        MODIFIED: begin
                            data_bus_lv1_lv2_reg    <= cache_var[{index_snoop,blk_access_snoop}];
                            lv2_wr                  <= 1'b1;
                            if(lv2_wr_done) begin
                                data_in_bus_lv1_lv2_reg   <= 1'b1;
                                `CACHE_CURRENT_MESI_SNOOP <= updated_mesi_snoop;
                                shared_local              <= 1'b1;
                                lv2_wr                    <= 1'b0;
                            end
                        end
                        default: begin
                            data_bus_lv1_lv2_reg      <= cache_var[{index_snoop,blk_access_snoop}];
                            data_in_bus_lv1_lv2_reg   <= 1'b1;
                            shared_local              <= 1'b1;
                            `CACHE_CURRENT_MESI_SNOOP <= updated_mesi_snoop;
                        end
                    endcase
                end
            end
        end
        // snoop side - response to invalidate when no copy is present in this cache
        else if(!blk_hit_snoop && (bus_lv1_lv2_gnt_proc != 1'b1)) begin
            // invalidation_done should be high for one cycle only
            if(invalidate && !invalidation_done) begin
                invalidation_done         <= 1'b1;
            end
        end
    end

endmodule
